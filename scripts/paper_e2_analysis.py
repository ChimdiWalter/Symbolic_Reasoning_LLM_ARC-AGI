#!/usr/bin/env python3
"""Paper E2: accuracy up, truth down — gate-off vs gate-on (RENDER-VERIFIED).

Harness 'solved' = gate-accepted (test_correct is stored separately) — so
this analysis renders every accepted object program against the task's test
outputs itself.  Populations:
  gate-off: outputs/unified_harness_e2_gateoff (OBJECT_GATE_OFF=1)
  gate-on : outputs/unified_harness_v8 (fallback v7)
Output: outputs/paper_e2/report.json — accepted vs render-verified correct.
"""
import glob
import json
import os
import sys

sys.path.insert(0, ".")
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.types import ObjectProgram
from geocat_arc.object_reasoning.actions import render_program

chal = json.load(open("data/arc/arc-agi_training_challenges.json"))
sols = json.load(open("data/arc/arc-agi_training_solutions.json"))
GATEOFF = "outputs/unified_harness_e2_gateoff"
BASE = "outputs/unified_harness_v8" \
    if os.path.exists("outputs/unified_harness_v8/results.json") \
    else "outputs/unified_harness_v7"


def object_stats(run_dir):
    accepted = correct = 0
    by_class = {}
    for f in glob.glob(f"{run_dir}/object/programs/*.json"):
        tid = os.path.basename(f)[:-5]
        try:
            prog = ObjectProgram.from_dict(json.load(open(f)))
        except Exception:
            continue
        accepted += 1
        pc = prog.worst_parameter_class.value
        ok = False
        try:
            ok = all(render_program(prog, Grid.from_list(c["input"])).to_list()
                     == sols[tid][i]
                     for i, c in enumerate(chal[tid]["test"]))
        except Exception:
            ok = False
        correct += ok
        n, k = by_class.get(pc, (0, 0))
        by_class[pc] = (n + 1, k + ok)
    return {"accepted": accepted, "render_verified_correct": correct,
            "precision": correct / accepted if accepted else None,
            "by_parameter_class": {
                pc: {"n": n, "correct": k, "precision": k / n}
                for pc, (n, k) in sorted(by_class.items())},
            "harness_reported_solved":
                json.load(open(f"{run_dir}/results.json"))["total_solved"]}


report = {"gate_off": object_stats(GATEOFF),
          "gate_on": object_stats(BASE),
          "gate_off_dir": GATEOFF, "gate_on_dir": BASE,
          "note": "harness 'solved'=gate-accepted; correctness here is "
                  "render-verified against test outputs (measurement only)"}
os.makedirs("outputs/paper_e2", exist_ok=True)
json.dump(report, open("outputs/paper_e2/report.json", "w"), indent=1)
print(json.dumps(report, indent=1))
