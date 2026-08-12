#!/usr/bin/env python3
"""Calibrated CSR — the graduated-certificate table (paper section).

One table over a gated run + its gate-off counterpart: every program the
system could emit, stratified by CERTIFICATE CLASS, with render-verified
precision per class.  Classes (strongest first):

  certified/<param_class>    — LOO-by-reinduction passed (the gate)
  uncertified/<param_class>  — train-perfect canonical winners the gate
                               rejected (gate-off acceptances)

The claim this table carries: certificate class is a CALIBRATED confidence
signal — precision decreases monotonically down the hierarchy, measured
without any access to test data at induction time.

Usage: paper_calibrated_csr.py GATED_DIR GATEOFF_DIR OUT_JSON
"""
import glob
import json
import os
import sys

sys.path.insert(0, ".")
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.types import ObjectProgram
from geocat_arc.object_reasoning.actions import render_program

gated_dir, gateoff_dir, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
chal = json.load(open("data/arc/arc-agi_training_challenges.json"))
sols = json.load(open("data/arc/arc-agi_training_solutions.json"))


def verified(prog, tid):
    try:
        return all(render_program(prog, Grid.from_list(c["input"])).to_list()
                   == sols[tid][i]
                   for i, c in enumerate(chal[tid]["test"]))
    except Exception:
        return False


def population(run_dir):
    out = {}
    for f in glob.glob(f"{run_dir}/object/programs/*.json"):
        tid = os.path.basename(f)[:-5]
        try:
            prog = ObjectProgram.from_dict(json.load(open(f)))
        except Exception:
            continue
        out[tid] = (prog.worst_parameter_class.value, verified(prog, tid))
    return out


gated = population(gated_dir)
gateoff = population(gateoff_dir)

table = {}
for tid, (pc, ok) in gated.items():
    key = f"certified/{pc}"
    n, k = table.get(key, (0, 0))
    table[key] = (n + 1, k + ok)
for tid, (pc, ok) in gateoff.items():
    if tid in gated:
        continue                      # certified dominates
    key = f"uncertified/{pc}"
    n, k = table.get(key, (0, 0))
    table[key] = (n + 1, k + ok)

ORDER = ["certified/relational", "certified/feature",
         "certified/induced_map", "certified/constant",
         "uncertified/relational", "uncertified/feature",
         "uncertified/induced_map", "uncertified/constant"]
report = {"classes": {k: {"n": table[k][0], "correct": table[k][1],
                          "precision": round(table[k][1] / table[k][0], 3)}
                      for k in ORDER if k in table},
          "gated_dir": gated_dir, "gateoff_dir": gateoff_dir,
          "reading": "certificate class is a calibrated confidence signal; "
                     "attempt policies read straight off this table"}
json.dump(report, open(out_path, "w"), indent=1)
print(json.dumps(report["classes"], indent=1))
