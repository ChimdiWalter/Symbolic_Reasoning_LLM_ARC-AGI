#!/usr/bin/env python3
"""Paper experiments E1 + E4 (artifact-only; no new induction).

E1 — Gate calibration: P(test-correct | LOO-certified) vs
     P(test-correct | train-perfect but LOO-REJECTED).
     Certified side: accepted object programs from harness runs (their
     harness records carry test_correct). Rejected side: near-solve rows
     with failure_stage == 'loo' (train-perfect by construction) — their
     partial programs are rendered against the task's test input here,
     ONLY for measurement (never fed back to any solver).
E4 — Test precision stratified by worst parameter class over the same
     populations.

Outputs: outputs/paper_e1_e4/report.json + printed tables.
"""
import glob
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, ".")
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.types import ObjectProgram
from geocat_arc.object_reasoning.actions import render_program

RUNS = ["outputs/unified_harness_v7", "outputs/unified_harness_v6",
        "outputs/unified_harness_v5"]
chal = json.load(open("data/arc/arc-agi_training_challenges.json"))
sols = json.load(open("data/arc/arc-agi_training_solutions.json"))


def test_correct_of(prog, tid) -> bool:
    try:
        t = chal[tid]["test"]
        for i, case in enumerate(t):
            pred = render_program(prog, Grid.from_list(case["input"]))
            if pred.to_list() != sols[tid][i]:
                return False
        return True
    except Exception:
        return False


certified = {}   # tid -> (param_class, test_correct)
rejected = {}
for run in RUNS:
    # certified: accepted programs (first run wins — newest first)
    for f in glob.glob(f"{run}/object/programs/*.json"):
        tid = os.path.basename(f)[:-5]
        if tid in certified:
            continue
        try:
            d = json.load(open(f))
            prog = ObjectProgram.from_dict(d)
            pc = prog.worst_parameter_class.value
            certified[tid] = (pc, test_correct_of(prog, tid))
        except Exception:
            pass
    # rejected train-perfect: loo-stage near-solves with full partials
    for f in glob.glob(f"{run}/object/near_solve_parts/*.jsonl"):
        tid = os.path.basename(f)[:-6]
        if tid in rejected or tid in certified:
            continue
        try:
            r = json.loads(open(f).readline())
            if r.get("failure_stage") != "loo":
                continue
            pp = r.get("program_partial")
            if not (isinstance(pp, dict) and pp.get("rules")):
                continue
            prog = ObjectProgram.from_dict(pp)
            pc = prog.worst_parameter_class.value
            rejected[tid] = (pc, test_correct_of(prog, tid))
        except Exception:
            pass


def precision(pop):
    n = len(pop)
    k = sum(1 for _, ok in pop.values() if ok)
    return n, k, (k / n if n else float("nan"))


n_c, k_c, p_c = precision(certified)
n_r, k_r, p_r = precision(rejected)
by_class = defaultdict(lambda: [0, 0])
for pop, tag in ((certified, "certified"), (rejected, "rejected")):
    for pc, ok in pop.values():
        key = (tag, pc)
        by_class[key][0] += 1
        by_class[key][1] += int(ok)

report = {
    "E1_gate_calibration": {
        "certified": {"n": n_c, "test_correct": k_c, "precision": p_c},
        "rejected_train_perfect": {"n": n_r, "test_correct": k_r,
                                   "precision": p_r},
    },
    "E4_by_parameter_class": {
        f"{tag}/{pc}": {"n": n, "test_correct": k,
                        "precision": (k / n if n else None)}
        for (tag, pc), (n, k) in sorted(by_class.items())
    },
    "runs_used": RUNS,
}
os.makedirs("outputs/paper_e1_e4", exist_ok=True)
json.dump(report, open("outputs/paper_e1_e4/report.json", "w"), indent=1)
print(json.dumps(report, indent=1))
