"""NVARC / native-CORA complementarity on the 240 stand-in tasks (DEVELOPMENT; contaminated for both systems).

  python scripts/nvarc_cora_complementarity.py   -> outputs/complementarity/standin_paired.json

The stand-in tasks are ARC-AGI-2 TRAINING tasks. NVARC's checkpoint was trained on that set, and CORA's frozen
library was built on it, so this measures mechanics, not generalization.

Arms, per test output:
- A: NVARC's two attempts.
- B: native CORA's two attempts (the Kaggle committed runs, unchanged).
- C: NVARC attempt 1, plus NVARC attempt 2 where it is genuine; otherwise CORA's first non-default answer.
  C never displaces a genuine NVARC answer.

Answers are read only here, from the pinned training solutions; nothing is selected with them.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_pilot import bundle as B, evaluator as EV                     # noqa: E402

DEP = os.path.join(HERE, "outputs", "kaggle_deploy")
DEFAULT = ([[0]], [], None)


def main():
    nv = json.load(open(os.path.join(DEP, "neural_v1_full_run1", "submission.json")))
    co = json.load(open(os.path.join(DEP, "native_v1", "kaggle_run_v1", "submission.json")))
    sol = EV.load_pinned(B.SOLUTIONS, B.SOLUTIONS_SHA256)
    score = {"A": 0.0, "B": 0.0, "C": 0.0}
    pos = {"positions": 0, "A": 0, "B": 0, "C": 0, "B_only": 0, "A_only": 0, "both": 0, "C_added": 0, "C_lost": 0,
           "nvarc_a2_empty": 0, "cora_fills": 0, "cora_fill_correct": 0, "cora_claims": 0, "cora_claims_correct": 0}
    tasks = 0
    for tid in sorted(nv):
        if tid not in sol or tid not in co:
            continue
        tasks += 1
        per = {"A": 0, "B": 0, "C": 0}
        for i, truth in enumerate(sol[tid]):
            n1, n2 = nv[tid][i].get("attempt_1"), nv[tid][i].get("attempt_2")
            c1, c2 = co[tid][i].get("attempt_1"), co[tid][i].get("attempt_2")
            cfirst = next((g for g in (c1, c2) if g not in DEFAULT), None)
            fill = n2 if n2 not in DEFAULT else cfirst
            a, b, c = truth in (n1, n2), truth in (c1, c2), truth in (n1, fill)
            pos["positions"] += 1
            pos["nvarc_a2_empty"] += n2 in DEFAULT
            pos["cora_fills"] += n2 in DEFAULT and cfirst is not None
            pos["cora_fill_correct"] += n2 in DEFAULT and cfirst is not None and cfirst == truth
            pos["cora_claims"] += cfirst is not None
            pos["cora_claims_correct"] += b
            for k, v in (("A", a), ("B", b), ("C", c)):
                pos[k] += v
                per[k] += v
            pos["both"] += a and b
            pos["A_only"] += a and not b
            pos["B_only"] += b and not a
            pos["C_added"] += c and not a
            pos["C_lost"] += a and not c
        for k in per:
            score[k] += per[k] / len(sol[tid])
    res = {"tasks": tasks, "positions": pos, "task_score_pct": {k: round(100 * v / tasks, 2) for k, v in score.items()},
           "contamination": "training tasks: NVARC trained on ARC-AGI-2 training; CORA's library was built on it",
           "official_public": {"NVARC": 27.64, "native_CORA": 0.00}}
    json.dump(res, open(os.path.join(HERE, "outputs", "complementarity", "standin_paired.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
