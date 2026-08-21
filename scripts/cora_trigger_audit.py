"""How often does the expression phase fire, and what does it cost?

Reports the trigger rate over the Experience split and the cost of the
phase itself, so the compute policy is a measured fact before the
meta-language is enlarged.  Analysis only; opens Experience tasks alone.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geocat_arc.object_reasoning import meta_induction as MI  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"


def main():
    challenges = json.loads(
        (ROOT / "data" / "arc-agi_training_challenges.json").read_text())
    manifest = json.loads((ROOT / "outputs" / "lockbox" / "manifest.json").read_text())
    tasks = manifest["tasks"]
    split = ({t["task_id"]: t["split"] for t in tasks} if isinstance(tasks, list)
             else {k: v["split"] for k, v in tasks.items()})
    experience = sorted(t for t, s in split.items() if s == "experience")
    fired = solved_by_search = 0
    seconds = 0.0
    hypotheses = 0
    found_tasks = []
    for tid in experience:
        pairs = [(np.array(p["input"]), np.array(p["output"]))
                 for p in challenges[tid]["train"]]
        if not MI.trigger_fires(pairs):
            continue
        fired += 1
        started = time.monotonic()
        asts, stats = MI.search(pairs)
        seconds += time.monotonic() - started
        hypotheses += stats.hypotheses
        if asts:
            solved_by_search += 1
            found_tasks.append(tid)
    report = {"experience_tasks": len(experience),
              "trigger_fired": fired,
              "trigger_rate": round(fired / len(experience), 4),
              "search_found_a_program": solved_by_search,
              "found_tasks": found_tasks,
              "total_seconds": round(seconds, 1),
              "seconds_per_fired_task": round(seconds / max(fired, 1), 3),
              "total_hypotheses": hypotheses,
              "hypotheses_per_fired_task": round(hypotheses / max(fired, 1), 1)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "trigger_audit.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
